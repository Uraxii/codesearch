const http = require('http');

function fetchData(url) {
    return http.get(url);
}

function processRequest(req, res) {
    const body = req.body;
    res.send(body);
}

class WebRequest {
    constructor(endpoint) {
        this.endpoint = endpoint;
    }

    send() {
        return fetch(this.endpoint);
    }
}

class HttpRequest {
    constructor(url) {
        this.url = url;
    }

    execute() {
        return new Promise((resolve) => resolve(this.url));
    }
}
