// DEMO FILE — intentional security vulnerabilities for codesearch demonstration
using System;
using System.Security.Cryptography;
using System.Text;

namespace Demo
{
    public class AuthService
    {
        // VULN: Hardcoded secret used to sign tokens
        private static readonly string JwtSecret = "my-super-secret-key-do-not-share";

        // VULN: MD5 used for password hashing (collision-vulnerable, no salt)
        public string HashPassword(string password)
        {
            using var md5 = MD5.Create();
            byte[] hash = md5.ComputeHash(Encoding.UTF8.GetBytes(password));
            return BitConverter.ToString(hash).Replace("-", "").ToLower();
        }

        // VULN: SHA1 used for integrity check (broken, deprecated for security)
        public string ComputeChecksum(string data)
        {
            using var sha1 = SHA1.Create();
            byte[] hash = sha1.ComputeHash(Encoding.UTF8.GetBytes(data));
            return Convert.ToBase64String(hash);
        }

        // VULN: System.Random used for security-sensitive token generation
        // (predictable seed, not cryptographically secure)
        public string GenerateSessionToken()
        {
            var rng = new Random();
            return rng.Next(100000, 999999).ToString();
        }

        // VULN: System.Random used for password reset code
        public int GeneratePasswordResetCode()
        {
            var random = new Random(Environment.TickCount);
            return random.Next(1000, 9999);
        }

        // VULN: DES encryption (56-bit key, broken)
        public byte[] EncryptLegacy(byte[] data, byte[] key)
        {
            using var des = DES.Create();
            des.Key = key;
            var encryptor = des.CreateEncryptor();
            return encryptor.TransformFinalBlock(data, 0, data.Length);
        }

        // VULN: RC2 encryption (key size ≤128 bits, deprecated)
        public byte[] EncryptData(byte[] data, byte[] key)
        {
            using var rc2 = RC2.Create();
            rc2.Key = key;
            var encryptor = rc2.CreateEncryptor();
            return encryptor.TransformFinalBlock(data, 0, data.Length);
        }
    }
}
