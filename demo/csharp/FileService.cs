// DEMO FILE — intentional security vulnerabilities for codesearch demonstration
using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.Serialization.Formatters.Binary;

namespace Demo
{
    public class FileService
    {
        private const string BaseDirectory = "/var/app/uploads";

        // VULN: Path traversal — user-supplied filename not sanitised
        // Attacker can pass "../../../etc/passwd" to read arbitrary files
        public string ReadFile(string filename)
        {
            string fullPath = Path.Combine(BaseDirectory, filename);
            return File.ReadAllText(fullPath);
        }

        // VULN: Path traversal in write path
        public void SaveFile(string filename, string content)
        {
            string destination = BaseDirectory + "/" + filename;
            File.WriteAllText(destination, content);
        }

        // VULN: Command injection — user input passed directly to shell
        // Attacker can pass "report.pdf; rm -rf /" as filename
        public string ConvertFile(string filename)
        {
            var proc = Process.Start("convert", filename + " output.png");
            proc.WaitForExit();
            return "output.png";
        }

        // VULN: Command injection via ProcessStartInfo with shell execute
        public void OpenFile(string userPath)
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = "sh",
                Arguments = "-c \"open " + userPath + "\"",
                UseShellExecute = true,
            };
            Process.Start(startInfo);
        }

        // VULN: Unsafe deserialisation — BinaryFormatter can execute arbitrary code
        // during deserialisation of attacker-controlled data
        public object DeserializeObject(byte[] data)
        {
            using var ms = new MemoryStream(data);
            var formatter = new BinaryFormatter();
            return formatter.Deserialize(ms);
        }

        // VULN: Unsafe deserialisation from file
        public object LoadFromFile(string path)
        {
            using var fs = File.OpenRead(path);
            var formatter = new BinaryFormatter();
            return formatter.Deserialize(fs);
        }
    }
}
