export interface AuthToken {
  access_token: string;
  token_type: string;
  expires_in: number;
  login_time: number;
}

export class AuthService {
  private static TOKEN_KEY = 'access_token';
  private static TOKEN_TYPE_KEY = 'token_type';
  private static EXPIRES_KEY = 'expires_in';
  private static LOGIN_TIME_KEY = 'login_time';

  static setToken(token: string, tokenType: string, expiresIn: number): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem(this.TOKEN_KEY, token);
      localStorage.setItem(this.TOKEN_TYPE_KEY, tokenType);
      localStorage.setItem(this.EXPIRES_KEY, expiresIn.toString());
      localStorage.setItem(this.LOGIN_TIME_KEY, Date.now().toString());
    }
  }

  static getToken(): AuthToken | null {
    if (typeof window === 'undefined') {
      return null;
    }

    const token = localStorage.getItem(this.TOKEN_KEY);
    const tokenType = localStorage.getItem(this.TOKEN_TYPE_KEY);
    const expiresIn = localStorage.getItem(this.EXPIRES_KEY);
    const loginTime = localStorage.getItem(this.LOGIN_TIME_KEY);

    if (!token || !tokenType || !expiresIn || !loginTime) {
      return null;
    }

    return {
      access_token: token,
      token_type: tokenType,
      expires_in: parseInt(expiresIn),
      login_time: parseInt(loginTime),
    };
  }

  static isTokenValid(): boolean {
    const authToken = this.getToken();

    if (!authToken) {
      return false;
    }

    // Check if token is expired
    const now = Date.now();
    const expirationTime = authToken.login_time + (authToken.expires_in * 1000);

    if (now >= expirationTime) {
      this.clearToken();
      return false;
    }

    return true;
  }

  static clearToken(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(this.TOKEN_KEY);
      localStorage.removeItem(this.TOKEN_TYPE_KEY);
      localStorage.removeItem(this.EXPIRES_KEY);
      localStorage.removeItem(this.LOGIN_TIME_KEY);
    }
  }

  static getAuthHeader(): string | null {
    const authToken = this.getToken();

    if (!authToken || !this.isTokenValid()) {
      return null;
    }

    return `${authToken.token_type} ${authToken.access_token}`;
  }

  static logout(): void {
    this.clearToken();
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
  }
}