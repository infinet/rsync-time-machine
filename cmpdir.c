#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <dirent.h>
#include <libgen.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <errno.h>

#define ONEK           1024.0
#define ONEM        1048576.0
#define ONEG     1073741824.0
#define ONET  1099511627776.0
#define PATH_MAX         4096
#define OLDDIR           0x01
#define NEWDIR           0x02
#define START_HASHBITS     12
/* max number of linked list before double the hash table size */
#define MAX_DEPTH           9

struct d_node {
    ino_t d_ino;
    char  *f_name;
    unsigned char  dir_id;
    unsigned char  depth;
    off_t f_size;
    struct d_node *prev;
    struct d_node *next;
};

static struct d_node **nodes;
static unsigned int hashsize = 1 << START_HASHBITS;

/* prototypes */
struct d_node *dalloc(char *d_name);
void add_or_update(struct d_node *dnp);
void dir_walk(char *dirpath, int dir_id);
void print_tree(char *olddir, char *newdir);
void upsizing(void);
void humanize_bytes(char buf[], int bufsize, unsigned long long n);
static inline int is_old_only(int dir_id);
static inline int is_new_only(int dir_id);
static inline uint32_t hash_inode(ino_t ino, unsigned int hashsize);
void debug_verify_hash(void);

void humanize_bytes(char buf[], int bufsize, unsigned long long n)
{
   double b;

   memset(buf, 0, bufsize);
   b = (double) n;
   if (b > ONET)
       snprintf(buf, bufsize, "%.2f TiB", b / ONET);
   else if (b > ONEG)
       snprintf(buf, bufsize, "%.2f GiB", b / ONEG);
   else if (b > ONEM)
       snprintf(buf, bufsize, "%.2f MiB", b / ONEM);
   else if (b > ONEK)
       snprintf(buf, bufsize, "%.2f KiB", b / ONEK);
   else
       snprintf(buf, bufsize, "%llu Bytes", n);
}


struct d_node *dalloc(char *d_name)
{
    struct d_node *dp;

    dp = malloc(sizeof(*dp));
    if (dp == NULL) {
        fprintf(stderr, "Error: d_node malloc failed\n");
        exit(2);
    }

    memset(dp, 0, sizeof(*dp));
    dp->f_name = strdup(d_name);
    dp->prev = NULL;
    dp->next = NULL;
    dp->dir_id = 0;
    dp->depth = 0;

    return dp;
}


void dir_walk(char *dirpath, int dir_id)
{
    DIR *dirp;
    struct dirent *dp;
    char path[PATH_MAX];
    struct stat statbuf;
    struct d_node *dnp;

    errno = 0;
    dirp = opendir(dirpath);
    if (dirp == NULL) {
        fprintf(stderr, "Error: opendir failed on %s, ", dirpath);
        switch (errno) {
        case EACCES:
            fprintf(stderr, "Permission denied.\n");
            break;
        case EBADF:
            fprintf(stderr, "fd is not a valid file descriptor.\n");
            break;
        case EMFILE:
            fprintf(stderr, "too many fd used by process.\n");
            break;
        case ENFILE:
            fprintf(stderr, "too many fd used by system.\n");
            break;
        case ENOENT:
            fprintf(stderr, "dir does not exist.\n");
            break;
        case ENOMEM:
            fprintf(stderr, "not enough memory.\n");
            break;
        case ENOTDIR:
            fprintf(stderr, "not a directory.\n");
            break;
        default:
            fprintf(stderr, "errno = %d.\n", errno);
            break;
        }
        return;
    }

    memset(&statbuf, 0, sizeof(statbuf));

    for (;;) {
        dp = readdir(dirp);
        if (dp == NULL) {
            if (errno != 0)
                fprintf(stderr, "readdir error, errno = %d.\n", errno);
            closedir(dirp);
            break;
        }

        if (strcmp(dp->d_name, ".") == 0 || strcmp(dp->d_name, "..") == 0)
            continue;

        memset(path, 0, PATH_MAX);
        strcat(path, dirpath);
        strcat(path, "/");
        strcat(path, dp->d_name);

        lstat(path, &statbuf);

        if (S_ISDIR(statbuf.st_mode)) {
            dir_walk(path, dir_id);
        } else {
            dnp = dalloc(path);
            dnp->d_ino = statbuf.st_ino;
            dnp->f_size = statbuf.st_size;
            dnp->dir_id = dir_id;
            add_or_update(dnp);
        }
    }
}


static inline int is_old_only(int dir_id)
{
    return dir_id == OLDDIR;
}


static inline int is_new_only(int dir_id)
{
    return dir_id == NEWDIR;
}


/* works very well for test set from dozens to 30K inodes */
static inline uint32_t hash_inode(ino_t ino, unsigned int hashsize)
{
    return ino & (hashsize - 1);
}


void print_tree(char *olddir, char *newdir)
{
    int i;
    struct d_node *np;
    unsigned long long removed = 0;
    unsigned long long added = 0;
    int cr, ca;
    char buf[64];

    cr = 0;
    ca = 0;
    for (i = 0; i < hashsize; i++) {
        for (np = nodes[i]; np != NULL; np = np->next) {
            if (is_old_only(np->dir_id)) {
                removed += np->f_size;
                cr++;
                humanize_bytes(buf, 64, np->f_size);
                printf("    Removed: %11s  %s\n", buf, np->f_name);
            }
        }
    }

    printf("\n-----------------------------------------------------------\n\n");
    for (i = 0; i < hashsize; i++) {
        for (np = nodes[i]; np != NULL; np = np->next) {
            if (is_new_only(np->dir_id)) {
                added += np->f_size;
                ca++;
                humanize_bytes(buf, 64, np->f_size);
                printf("    New: %15s  %s\n", buf, np->f_name);
            }
        }
    }

    printf("\n-----------------------------------------------------------\n");
    humanize_bytes(buf, 64, removed);
    printf("Removed %5d files from %s, %s\n", cr, olddir, buf);
    humanize_bytes(buf, 64, added);
    printf("Added   %5d files to   %s, %s\n", ca, olddir, buf);
}


void add_or_update(struct d_node *dnp)
{
    int i;
    struct d_node *np;

    i = hash_inode(dnp->d_ino, hashsize);
    for (np = nodes[i]; np != NULL; np = np->next) {
        if (np->d_ino == dnp->d_ino) {
            np->dir_id |= dnp->dir_id;
            free(dnp->f_name);
            free(dnp);
            return;
        }
    }

    dnp->next = nodes[i];
    if (dnp->next != NULL) {
        dnp->next->prev = dnp;
        dnp->depth = dnp->next->depth + 1;
    }
    nodes[i] = dnp;

    if (nodes[i]->depth > MAX_DEPTH)
        upsizing();
}


void upsizing(void)
{
    struct d_node **old_nodes;
    struct d_node *np, *next;
    int i, k;
    unsigned int old_hashsize;

    //debug_verify_hash();
    old_nodes = nodes;
    old_hashsize = hashsize;
    hashsize *= 2;
    nodes = malloc(hashsize * sizeof(struct d_node *));
    if (nodes == NULL) {
        fprintf(stderr, "Error: malloc for new nodes failed\n");
        exit(2);
    }

    for (i = 0; i < hashsize; i++)
        nodes[i] = NULL;

    for (i = 0; i < old_hashsize; i++) {
        np = old_nodes[i];
        while (np != NULL) {
            next = np->next;
            k = hash_inode(np->d_ino, hashsize);
            if (nodes[k] == NULL)
                np->depth = 0;  /* reset depth for new hash table*/
            else
                np->depth = nodes[k]->depth + 1;

            if (nodes[k] != NULL)
                nodes[k]->prev = np;

            np->prev = NULL;
            np->next = nodes[k];
            nodes[k] = np;
            np = next;

        }
    }

    free(old_nodes);
    //printf("debug: end upsizing\n");
    return;
}

void debug_verify_hash(void)
{
    int i, max;
    struct d_node *np;
    double used, md;

    used = 0.0;
    md = 0.0;
    max = -1;
    for (i = 0; i < hashsize; i++) {
        np = nodes[i];
        if (np) {
            used += 1.0;
            md += np->depth;
            if (np->depth > max)
                max = np->depth;
        }
    }

    printf("total %d bucket, %.0f used, %.1f%%, depth: mean  %.1f, max %d\n",
            hashsize,
            used,
            100.0 * used / hashsize,
            md / used, max);
}


int main(int argc, char *argv[])
{
    int i;

    if (argc < 3) {
        printf("Usage: %s old_dir new_dir\n", basename(argv[0]));
        exit(2);
    }

    nodes = malloc(hashsize * sizeof(struct d_node *));
    if (nodes == NULL) {
        fprintf(stderr, "Error: initial nodes malloc failed\n");
        exit(2);
    }

    for (i = 0; i < hashsize; i++)
        nodes[i] = NULL;

    dir_walk(argv[1], OLDDIR);   /* dir to compare with */
    dir_walk(argv[2], NEWDIR);   /* new dir */
    print_tree(argv[1], argv[2]);

    return 0;
}
