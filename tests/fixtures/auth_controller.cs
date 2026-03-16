using Microsoft.AspNetCore.Mvc;
[ApiController]
public class AuthController : ControllerBase {
    [HttpGet("login")]
    public IActionResult Login(string username, string password, string apiKey) => Ok();
    [HttpPost("register")]
    public IActionResult Register(string username, string password) => Ok();
    [HttpGet("search")]
    public IActionResult Search(string query) => Ok();
}
