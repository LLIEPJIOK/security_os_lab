.PHONY: test
test: 
	javac decryptor/Main.java decryptor/AESCrypt.java
	java decryptor/Main ./data/test.jpg.enc ./data/test.jpg

.PHONY: clean
clean:
	rm -f decryptor/*.class
