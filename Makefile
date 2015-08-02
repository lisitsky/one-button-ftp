
# start settings
DIST=dist
# change NAME also in setup.py and resource/config.txt
NAME=FotoWoman
EXT=exe

# final name and location of the built program
FINAL=$(DIST)/$(NAME).$(EXT)

# external programs
7ZIPDIR="C:\Program Files\7-Zip"
RESHACKER="/c/Program\ Files/Resource\ Hacker/ResourceHacker.exe"

# intermediate steps

# no icon version of program 
NOICON=$(DIST)/$(NAME)_no_icon.$(EXT)

# name of .7z archive
7Z_BASENAME=$(NAME).7z
7Z=$(DIST)/$(7Z_BASENAME)

# folder with ready .exe
PROGDIR=$(DIST)/$(NAME)

all: $(FINAL)


$(FINAL): $(NOICON)
	# change icon
	"$(RESHACKER)" -addoverwrite $(NOICON), $(FINAL), resources/favicon.ico, ICONGROUP, MAINICON, 0


$(NOICON): $(7Z)
	#build autorunning sfx with default icon
	cat $(7ZIPDIR)/7zS.sfx resources/config.txt $(7Z) > $(NOICON)


$(7Z): exe
	# compress program folder to .7z
	cd $(DIST);  $(7ZIPDIR)\\\7z.exe a  $(7Z_BASENAME)  $(NAME)


exe: 
	# build program itself
	python setup.py py2exe


clean:
	rm -rf $(DIST)/*
