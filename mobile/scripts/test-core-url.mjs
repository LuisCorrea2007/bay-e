import assert from "node:assert/strict";
import { isPrivateLanHost, normalizeCoreUrl } from "../src/core-url.js";

for (const host of ["10.0.0.4","172.16.0.2","172.31.255.9","192.168.1.20","127.0.0.1","localhost","baye.local","fd00::1","fe80::1"]) {
  assert.equal(isPrivateLanHost(host), true, host);
}
for (const host of ["8.8.8.8","172.15.0.1","172.32.0.1","192.0.2.5","example.com"]) {
  assert.equal(isPrivateLanHost(host), false, host);
}
assert.equal(normalizeCoreUrl("http://192.168.1.20:8300/"), "http://192.168.1.20:8300");
assert.equal(normalizeCoreUrl("https://baye.example.com/"), "https://baye.example.com");
assert.throws(() => normalizeCoreUrl("http://example.com:8300"), /HTTP solo/);
assert.throws(() => normalizeCoreUrl("ftp://192.168.1.20"), /http:\/\/ o https:\/\//);
assert.throws(() => normalizeCoreUrl("http://user:pass@192.168.1.20"), /credenciales/);
console.log("BAY-E mobile Core URL policy OK");
