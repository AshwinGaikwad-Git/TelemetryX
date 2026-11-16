import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Team from "../components/industrial/team";
import AuthScreen from "../components/industrial/auth-screen";
import { Role } from "../lib/industrial-api";

const profile = { id: "owner", name: "Owner", email: "owner@example.com", companies: [] };
const members = [
  { id: "owner", name: "Owner", email: "owner@example.com", role: "admin" as Role },
  { id: "member", name: "Engineer", email: "engineer@example.com", role: "engineer" as Role },
];
const run = async (operation: () => Promise<unknown>) => { await operation(); };
function team(role: Role = "admin") {
  const onProfile = vi.fn();
  render(<Team base="/companies/c1" members={members} keys={[{ id: "key-1", name: "Gateway", active: true, created_at: "2026-11-17T10:00:00Z" }]} events={[]} role={role} run={run} busy={false} onProfile={onProfile} userId="owner" />);
  return onProfile;
}
function responses(value: unknown = profile) {
  const fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => value }));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}
afterEach(() => vi.unstubAllGlobals());

describe("team access and integration controls", () => {
  it("hides invitation key and role-management controls from viewers", () => {
    team("viewer");
    expect(screen.queryByRole("button", { name: "Create private invitation" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Generate ingestion key" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Role for Engineer")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove access" })).not.toBeInTheDocument();
  });
  it("creates a private invitation and dismisses its one-time display", async () => {
    const fetch = responses({ token: "one-time-invitation-token" });
    team();
    fireEvent.change(screen.getByLabelText("Invite member email"), { target: { value: " invited@example.com " } });
    fireEvent.click(screen.getByRole("button", { name: "Create private invitation" }));
    expect(await screen.findByText("one-time-invitation-token")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/v1/industrial/companies/c1/invitations", expect.objectContaining({ method: "POST" }));
    fireEvent.click(screen.getByRole("button", { name: "I have saved it privately" }));
    expect(screen.queryByText("one-time-invitation-token")).not.toBeInTheDocument();
  });
  it("allows engineers to generate and revoke company-scoped ingestion credentials", async () => {
    const fetch = responses({ token: "new-ingestion-key" });
    team("engineer");
    fireEvent.change(screen.getByLabelText("Integration name"), { target: { value: "Plant & Line 1" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate ingestion key" }));
    expect(await screen.findByText("new-ingestion-key")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/v1/industrial/companies/c1/ingestion-keys?name=Plant%20%26%20Line%201", expect.objectContaining({ method: "POST" }));
    fireEvent.click(screen.getByRole("button", { name: "Revoke key" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/v1/industrial/companies/c1/ingestion-keys/key-1/revoke", expect.objectContaining({ method: "POST" })));
  });
  it("refreshes the profile after accepting an invitation", async () => {
    responses();
    const onProfile = team("viewer");
    fireEvent.change(screen.getByLabelText("Invitation token"), { target: { value: "invitation-token-123456789" } });
    fireEvent.click(screen.getByRole("button", { name: "Accept invitation" }));
    await waitFor(() => expect(onProfile).toHaveBeenCalledWith(profile));
  });
  it("creates a separate company and refreshes membership", async () => {
    const fetch = responses();
    const onProfile = team();
    fireEvent.change(screen.getByLabelText("New company name"), { target: { value: "Second Plant" } });
    fireEvent.click(screen.getByRole("button", { name: "Create company" }));
    await waitFor(() => expect(onProfile).toHaveBeenCalledWith(profile));
    expect(fetch).toHaveBeenCalledWith("/api/v1/industrial/auth/companies", expect.objectContaining({ body: JSON.stringify({ name: "Second Plant" }) }));
  });
  it("submits role changes and access removal for another member", async () => {
    const fetch = responses();
    team();
    fireEvent.change(screen.getByLabelText("Role for Engineer"), { target: { value: "viewer" } });
    fireEvent.click(screen.getByRole("button", { name: "Remove access" }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/v1/industrial/companies/c1/members/member", expect.objectContaining({ method: "PATCH", body: JSON.stringify({ role: "viewer" }) })));
    expect(fetch).toHaveBeenCalledWith("/api/v1/industrial/companies/c1/members/member", expect.objectContaining({ method: "DELETE" }));
  });
});

describe("authentication form recovery", () => {
  it("preserves password whitespace and trims descriptive registration fields", async () => {
    const fetch = responses();
    const signedIn = vi.fn();
    render(<AuthScreen onSignedIn={signedIn} />);
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: " Owner " } });
    fireEvent.change(screen.getByLabelText("Company name"), { target: { value: " Factory " } });
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "owner@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: " secret-password-123 " } });
    fireEvent.submit(screen.getByRole("button", { name: "Create my workspace" }).closest("form")!);
    await waitFor(() => expect(signedIn).toHaveBeenCalledWith(profile));
    expect(fetch).toHaveBeenCalledWith("/api/v1/industrial/auth/register", expect.objectContaining({ body: JSON.stringify({ email: "owner@example.com", password: " secret-password-123 ", name: "Owner", company_name: "Factory" }) }));
  });
  it("recovers the sign-in button after a rejected login", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 401, json: async () => ({ detail: "Email or password is incorrect" }) })));
    render(<AuthScreen onSignedIn={vi.fn()} />);
    fireEvent.click(screen.getAllByRole("button", { name: "Sign in" })[0]);
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "owner@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "long-password-123" } });
    const button = screen.getAllByRole("button", { name: "Sign in" })[1];
    fireEvent.submit(button.closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect");
    expect(button).toBeEnabled();
  });
});
