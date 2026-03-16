public class C {
    [HttpGet("login")]
    public IActionResult Login(string username, string password) { return Ok(); }
}
