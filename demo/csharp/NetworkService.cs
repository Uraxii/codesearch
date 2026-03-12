// DEMO FILE — intentional security vulnerabilities for codesearch demonstration
using System;
using System.Net;
using System.Net.Http;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using Newtonsoft.Json;

namespace Demo
{
    public class NetworkService
    {
        // VULN: Hardcoded API key embedded in source
        private const string ApiKey = "sk-proj-aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890";
        private const string WebhookSecret = "whsec_abcdef1234567890";

        // VULN: Disabling SSL/TLS certificate validation globally
        // Any certificate (including self-signed or attacker-controlled) is accepted
        public void DisableSslValidation()
        {
            ServicePointManager.ServerCertificateValidationCallback =
                delegate (object sender, X509Certificate cert, X509Chain chain, SslPolicyErrors errors)
                {
                    return true;  // accepts ALL certificates unconditionally
                };
        }

        // VULN: Disabled SSL via lambda — another common pattern
        public HttpClient CreateInsecureClient()
        {
            var handler = new HttpClientHandler
            {
                ServerCertificateCustomValidationCallback = (msg, cert, chain, errors) => true
            };
            return new HttpClient(handler);
        }

        // VULN: Unsafe JSON deserialisation with TypeNameHandling.All
        // Allows attackers to specify arbitrary .NET types in JSON payload
        public object DeserializeJson(string json)
        {
            var settings = new JsonSerializerSettings
            {
                TypeNameHandling = TypeNameHandling.All
            };
            return JsonConvert.DeserializeObject(json, settings);
        }

        // VULN: Sending credentials over plain HTTP
        public string FetchUserData(string userId)
        {
            string url = "http://internal-api/users/" + userId;
            using var client = new WebClient();
            client.Headers["Authorization"] = "Bearer " + ApiKey;
            return client.DownloadString(url);
        }

        // VULN: SSRF — user-controlled URL used in outbound request without validation
        public string FetchUrl(string targetUrl)
        {
            using var client = new WebClient();
            return client.DownloadString(targetUrl);
        }
    }
}
