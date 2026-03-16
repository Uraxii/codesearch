using Microsoft.AspNetCore.Mvc;
[ApiController]
public class OtpController : ControllerBase {
    [HttpGet("verify")]
    public IActionResult Verify(string otp, string pin, string pwd) => Ok();
    [HttpGet("auth")]
    public IActionResult Authenticate(string auth, string ssn, string cvv) => Ok();
    [HttpGet("safe")]
    public IActionResult Safe(string userId, string page) => Ok();
}
