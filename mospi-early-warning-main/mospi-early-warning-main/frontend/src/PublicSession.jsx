import { createContext, useContext } from "react";

/**
 * Session facts the public surfaces need but cannot get from `useAuth`.
 *
 * An anonymous visitor has no `user` object at all, so the shell's usual
 * "sign out" affordance has nothing to render. Publishing the callbacks here
 * lets the read-only chrome offer a sign-in path without the pages having to
 * know whether they are public or not.
 *
 * This lives in its own module rather than in `PublicRoutes` because the
 * route table imports `AppShell`, and `AppShell` needs to read this context —
 * declaring it in the route table would make those two modules import each
 * other.
 */
const PublicSessionContext = createContext(null);

export const PublicSessionProvider = PublicSessionContext.Provider;

export function usePublicSession() {
  return useContext(PublicSessionContext) || {};
}
