interface Request {
    url: string;
    method: string;
}

function makeWebRequest(req: WebRequest): void {
    req.send();
}

function makeHttpRequest(req: HttpRequest): void {
    req.execute();
}

class WebRequest implements Request {
    url: string;
    method: string = "GET";

    constructor(url: string) {
        this.url = url;
    }

    send(): Promise<Response> {
        return fetch(this.url);
    }
}

class HttpRequest implements Request {
    url: string;
    method: string = "POST";

    constructor(url: string) {
        this.url = url;
    }

    execute(): Promise<Response> {
        return fetch(this.url, { method: this.method });
    }
}

function acceptsString(input: string): string {
    return input.trim();
}
