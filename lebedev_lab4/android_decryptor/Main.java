package android_decryptor;

import java.io.File;

public class Main {
	public static void main(String[] args) throws Exception {
		File input = new File(args[0]);
		String outputDir = args[1];

		AESCrypt aesCrypt = new AESCrypt();

		if (!input.exists()) {
			System.err.println("Input path does not exist: " + input);
			return;
		}

		new File(outputDir).mkdirs();

		if (input.isFile()) {
			String outPath = outputDir + "/" + input.getName().replace(".enc", "");
			aesCrypt.decrypt(input.getAbsolutePath(), outPath);
		} else if (input.isDirectory()) {
			File[] files = input.listFiles();
			if (files == null)
				return;

			for (File f : files) {
				if (!f.isFile())
					continue;
				if (!f.getName().endsWith(".enc"))
					continue;

				String outPath = outputDir + "/" + f.getName().replace(".enc", "");
				aesCrypt.decrypt(f.getAbsolutePath(), outPath);
			}
		}
	}
}
