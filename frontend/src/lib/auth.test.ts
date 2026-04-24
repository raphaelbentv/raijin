import { beforeEach, describe, expect, it } from "vitest";
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  isAuthenticated,
  setAccessToken,
  setTokens,
} from "./auth";

describe("auth token storage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("stores and clears token pairs", () => {
    setTokens("access-1", "refresh-1");

    expect(getAccessToken()).toBe("access-1");
    expect(getRefreshToken()).toBe("refresh-1");
    expect(isAuthenticated()).toBe(true);

    clearTokens();

    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("updates only the access token after refresh", () => {
    setTokens("access-1", "refresh-1");
    setAccessToken("access-2");

    expect(getAccessToken()).toBe("access-2");
    expect(getRefreshToken()).toBe("refresh-1");
  });
});
