import assert from "node:assert/strict";

process.env.ADMIN_PASSWORD = "secret-password";

const { COOKIE_NAME, isAuthorized, sessionToken, validatePassword } = await import("../lib/auth.js");

function test(name, fn) {
  try {
    fn();
    console.log(`ok - ${name}`);
  } catch (error) {
    console.error(`not ok - ${name}`);
    throw error;
  }
}

test("validates the configured admin password", () => {
  assert.equal(validatePassword("secret-password"), true);
  assert.equal(validatePassword("wrong-password"), false);
});

test("authorizes requests with the session cookie", () => {
  const request = {
    cookies: {
      get(name) {
        return name === COOKIE_NAME ? { value: sessionToken() } : undefined;
      },
    },
  };

  assert.equal(isAuthorized(request), true);
});

test("rejects requests without the session cookie", () => {
  const request = {
    cookies: {
      get() {
        return undefined;
      },
    },
  };

  assert.equal(isAuthorized(request), false);
});
