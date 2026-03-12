using System;
using System.Net;

namespace MyApp
{
    public class WebRequestExample
    {
        public static void Main(string[] args)
        {
            var req = new WebRequest();
            HttpRequest httpReq = new HttpRequest("/path");
            req.GetResponse();
            WebRequest.Create("http://example.com");
        }

        private string Greet(string name)
        {
            return "Hello " + name;
        }

        public void ProcessRequest(WebRequest req)
        {
            req.GetResponse();
        }

        public void ProcessHttp(HttpRequest req)
        {
            req.Execute();
        }
    }

    public class HttpRequest
    {
        private string _path;

        public HttpRequest(string path)
        {
            _path = path;
        }

        public void Execute()
        {
            Console.WriteLine(_path);
        }
    }
}
