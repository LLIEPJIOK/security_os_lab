package decryptor;

public class Main {
	public static void main(String[] args) throws Exception {
		String file = args[0];
		String output = args[1];

		AESCrypt aesCrypt = new AESCrypt();
		aesCrypt.decrypt(file, output);
	}
}