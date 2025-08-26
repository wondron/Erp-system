import axios from "axios";

export interface UserOut {
  id: number;
  first_name: string;
  last_name: string;
}

export interface UserCreateIn {
  first_name: string;
  last_name: string;
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE,
  headers: { "Content-Type": "application/json" },
  timeout: 10000,
});

// POST /users  body: { first_name, last_name } -> UserOut
export async function createUser(body: UserCreateIn): Promise<UserOut> {
  const { data } = await http.post<UserOut>("/users", body);
  return data;
}

// GET /users?last_name=张  -> UserOut[]
export async function listUsersByLastName(last_name: string): Promise<UserOut[]> {
  const { data } = await http.get<UserOut[]>("/users", { params: { last_name } });
  return data;
}
