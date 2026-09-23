"use client";

import { useCreateUser, useUpdateUser, useUsers } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { UserRole } from "@/lib/types";

const ROLES: UserRole[] = ["ADMIN", "NETWORK_ENGINEER", "IT_SUPPORT", "VIEWER"];

export default function UsersPage() {
  const { isAdmin, loading } = useAuth();
  const { data: users } = useUsers();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();

  if (!loading && !isAdmin) {
    return <div className="card text-gray-400">Access denied -- ADMIN only.</div>;
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-gray-100">Users</h1>

      <form
        className="card flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          const form = new FormData(e.currentTarget);
          createUser.mutate({
            email: String(form.get("email")),
            password: String(form.get("password")),
            full_name: String(form.get("full_name") || "") || undefined,
            role: String(form.get("role")),
          });
          e.currentTarget.reset();
        }}
      >
        <label className="flex flex-col gap-1 text-xs text-gray-400">
          Email
          <input name="email" type="email" required className="input" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-gray-400">
          Full name
          <input name="full_name" className="input" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-gray-400">
          Password
          <input name="password" type="password" required minLength={8} className="input" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-gray-400">
          Role
          <select name="role" className="input">
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="btn-primary" disabled={createUser.isPending}>
          Create user
        </button>
        {createUser.isError && <span className="text-xs text-red-400">{(createUser.error as Error).message}</span>}
      </form>

      <div className="card overflow-x-auto">
        <table className="table-base">
          <thead>
            <tr>
              <th>Email</th>
              <th>Name</th>
              <th>Role</th>
              <th>Active</th>
              <th>Last login</th>
            </tr>
          </thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id}>
                <td>{u.email}</td>
                <td>{u.full_name || "-"}</td>
                <td>
                  <select
                    className="input"
                    value={u.role}
                    onChange={(e) => updateUser.mutate({ id: u.id, payload: { role: e.target.value } })}
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    type="checkbox"
                    checked={u.is_active}
                    onChange={(e) => updateUser.mutate({ id: u.id, payload: { is_active: e.target.checked } })}
                  />
                </td>
                <td className="text-xs text-gray-400">{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "never"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
