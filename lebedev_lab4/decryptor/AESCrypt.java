package decryptor;

import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.security.MessageDigest;
import java.security.spec.AlgorithmParameterSpec;

import javax.crypto.Cipher;
import javax.crypto.CipherInputStream;
import javax.crypto.CipherOutputStream;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;

public class AESCrypt {
	private final Cipher cipher;
	private final SecretKeySpec key;
	private AlgorithmParameterSpec spec;
	private final String secret = "jndlasf074hr";

	public AESCrypt() throws Exception {
		MessageDigest var2 = MessageDigest.getInstance("SHA-256");
		var2.update(secret.getBytes("UTF-8"));
		byte[] var3 = new byte[32];
		System.arraycopy(var2.digest(), 0, var3, 0, var3.length);
		this.cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
		this.key = new SecretKeySpec(var3, "AES");
		this.spec = this.getIV();
	}

	public void decrypt(String var1, String var2) throws Exception {
		FileInputStream var4 = new FileInputStream(var1);
		FileOutputStream var5 = new FileOutputStream(var2);
		this.cipher.init(2, this.key, this.spec);
		CipherInputStream var7 = new CipherInputStream(var4, this.cipher);
		byte[] var6 = new byte[8];

		while (true) {
			int var3 = var7.read(var6);
			if (var3 == -1) {
				var5.flush();
				var5.close();
				var7.close();
				return;
			}

			var5.write(var6, 0, var3);
		}
	}

	public void encrypt(String var1, String var2) throws Exception {
		FileInputStream var5 = new FileInputStream(var1);
		FileOutputStream var6 = new FileOutputStream(var2);
		this.cipher.init(1, this.key, this.spec);
		CipherOutputStream var7 = new CipherOutputStream(var6, this.cipher);
		byte[] var4 = new byte[8];

		while (true) {
			int var3 = var5.read(var4);
			if (var3 == -1) {
				var7.flush();
				var7.close();
				var5.close();
				return;
			}

			var7.write(var4, 0, var3);
		}
	}

	public AlgorithmParameterSpec getIV() {
		return new IvParameterSpec(new byte[16]);
	}
}
