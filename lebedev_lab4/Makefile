.PHONY: test
test: 
	@javac decryptor/Main.java decryptor/AESCrypt.java
	@java decryptor/Main ./data/test.jpg.enc ./data/test.jpg

.PHONY: clean
clean:
	@rm -f decryptor/*.class

.PHONY: android_decrypt
android_decrypt:
	@javac android_decryptor/Main.java android_decryptor/AESCrypt.java
	@java android_decryptor/Main $(input) $(output)

.PHONY: android_clean
android_clean:
	@rm -f android_decryptor/*.class
