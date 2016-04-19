
CC = gcc
CFLAGS = -Wall -O2
LIBS =

CMPDIR = cmpdir

# default target
.PHONY : all
all: $(CMPDIR)
	@echo all done!

OBJS =

CMPDIR_OBJS = $(OBJS)
CMPDIR_OBJS += cmpdir.o

#cmpdir.o:  cmpdir.h


$(CMPDIR): $(CMPDIR_OBJS)
	$(CC) $(CFLAGS) -o $(CMPDIR) $(CMPDIR_OBJS) $(LIBS)


.PHONY : clean
clean:
	rm -f *.o core a.out cmpdir
