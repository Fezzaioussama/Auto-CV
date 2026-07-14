import { ReactNode } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import {
  Navbar,
  NavbarBrand,
  NavbarContent,
  NavbarItem,
  Button,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
  Avatar,
} from "@heroui/react";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../lib/api";

const NAV_ITEMS = [
  { to: "/optimizer", label: "Optimizer" },
  { to: "/interview", label: "Interview Prep" },
  { to: "/workspace", label: "Workspace" },
  { to: "/how-it-works", label: "How it works" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  async function handleLogout() {
    try {
      await api.post("/logout");
    } catch {
      /* ignore — clear local state regardless */
    }
    setUser(null);
    navigate("/login");
  }

  const initials =
    user?.name?.trim().slice(0, 2).toUpperCase() ||
    user?.email?.slice(0, 2).toUpperCase() ||
    "AC";

  return (
    <div className="min-h-screen flex flex-col">
      <Navbar maxWidth="xl" className="bg-white/80 backdrop-blur border-b border-default-200">
        <NavbarBrand>
          <Link to="/" className="flex items-center gap-2 font-display text-lg font-extrabold">
            <img
              src="/static/assets/autocv-logo.png"
              alt=""
              aria-hidden
              className="h-8 w-8 rounded-md"
            />
            <span>
              Auto<span className="text-primary">CV</span>
            </span>
          </Link>
        </NavbarBrand>

        <NavbarContent className="hidden md:flex gap-4" justify="center">
          {NAV_ITEMS.map((item) => {
            const active = location.pathname.startsWith(item.to);
            return (
              <NavbarItem key={item.to} isActive={active}>
                <Link
                  to={item.to}
                  className={
                    active ? "text-primary font-semibold" : "text-default-600 hover:text-default-900"
                  }
                >
                  {item.label}
                </Link>
              </NavbarItem>
            );
          })}
        </NavbarContent>

        <NavbarContent justify="end">
          {user ? (
            <Dropdown placement="bottom-end">
              <DropdownTrigger>
                <Avatar
                  isBordered
                  showFallback
                  size="sm"
                  name={initials}
                  className="cursor-pointer"
                />
              </DropdownTrigger>
              <DropdownMenu aria-label="Account">
                <DropdownItem key="profile" textValue={user.email} className="h-14 gap-2">
                  <p className="text-xs text-default-500">Signed in as</p>
                  <p className="font-semibold truncate">{user.email}</p>
                </DropdownItem>
                <DropdownItem key="account" onPress={() => navigate("/account")}>
                  Account & privacy
                </DropdownItem>
                <DropdownItem key="workspace" onPress={() => navigate("/workspace")}>
                  Workspace
                </DropdownItem>
                <DropdownItem key="logout" color="danger" onPress={handleLogout}>
                  Sign out
                </DropdownItem>
              </DropdownMenu>
            </Dropdown>
          ) : (
            <>
              <NavbarItem className="hidden md:flex">
                <Link to="/login" className="text-default-600">
                  Sign in
                </Link>
              </NavbarItem>
              <NavbarItem>
                <Button as={Link} to="/register" color="primary" variant="flat" radius="full">
                  Get started
                </Button>
              </NavbarItem>
            </>
          )}
        </NavbarContent>
      </Navbar>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-default-200 bg-white py-8 mt-12">
        <div className="max-w-6xl mx-auto px-6 flex flex-wrap items-center justify-between gap-4 text-sm text-default-500">
          <div className="font-display font-bold">
            Auto<span className="text-primary">CV</span>
          </div>
          <div className="flex gap-4">
            <Link to="/privacy" className="hover:text-default-900">
              Privacy
            </Link>
            <Link to="/terms" className="hover:text-default-900">
              Terms
            </Link>
            <Link to="/how-it-works" className="hover:text-default-900">
              How it works
            </Link>
          </div>
          <div>AI-Powered LaTeX CV Generator · Your facts stay yours.</div>
        </div>
      </footer>
    </div>
  );
}
