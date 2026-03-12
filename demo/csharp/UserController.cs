// DEMO FILE — intentional security vulnerabilities for codesearch demonstration
using System;
using System.Data.SqlClient;
using System.Web;
using System.Web.Mvc;

namespace Demo
{
    public class UserController : Controller
    {
        // VULN: Hardcoded credentials
        private const string AdminPassword = "admin123!";
        private const string DbConnectionString = "Server=prod-db;Database=users;User=sa;Password=Passw0rd!";

        // VULN: SQL injection — user input concatenated directly into query string
        public ActionResult Search(string username)
        {
            string query = "SELECT * FROM Users WHERE Username = '" + username + "'";
            using var conn = new SqlConnection(DbConnectionString);
            using var cmd = new SqlCommand(query, conn);
            conn.Open();
            var reader = cmd.ExecuteReader();
            return View(reader);
        }

        // VULN: SQL injection via string.Format
        public ActionResult GetUser(int id, string filter)
        {
            string query = string.Format("SELECT * FROM Users WHERE Id = {0} AND Role = '{1}'", id, filter);
            using var conn = new SqlConnection(DbConnectionString);
            using var cmd = new SqlCommand(query, conn);
            conn.Open();
            return View(cmd.ExecuteReader());
        }

        // VULN: XSS — writing raw user input to response without encoding
        public void WriteComment(string comment)
        {
            Response.Write("<div class='comment'>" + comment + "</div>");
        }

        // VULN: XSS via interpolated string in HTML response
        public ActionResult Profile(string displayName)
        {
            string html = $"<h1>Welcome, {displayName}!</h1>";
            return Content(html, "text/html");
        }

        // Safe login for contrast: compares against hardcoded password (still a smell)
        public bool Login(string username, string password)
        {
            return username == "admin" && password == AdminPassword;
        }
    }
}
