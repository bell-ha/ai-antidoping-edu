import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router";
import { api, type SessionInfo } from "./api";
import { Shell } from "./components/Shell";
import { HOME_BY_ROLE, SessionContext } from "./session";
import { AdminAthlete } from "./pages/admin/AdminAthlete";
import { AdminAthletes } from "./pages/admin/AdminAthletes";
import { AdminSettings } from "./pages/admin/AdminSettings";
import { Architecture } from "./pages/Architecture";
import { Ask } from "./pages/Ask";
import { Check } from "./pages/Check";
import { Guide } from "./pages/athlete/Guide";
import { Home } from "./pages/athlete/Home";
import { Lesson } from "./pages/athlete/Lesson";
import { Library } from "./pages/Library";
import { Login } from "./pages/Login";

export default function App() {
  const [who, setWho] = useState<SessionInfo | null | undefined>(undefined);
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    api.whoami().then(setWho, () => setWho(null));
    api.demoCodes().then(() => setDemo(true), () => setDemo(false));
  }, []);

  const logout = useCallback(() => {
    api.logout().finally(() => setWho(null));
  }, []);

  if (who === undefined) return null;
  if (who === null) return <Login onLogin={setWho} />;

  return (
    <SessionContext.Provider value={{ who, demo, logout }}>
      <Routes>
        <Route element={<Shell />}>
          {who.role === "athlete" ? (
            <>
              <Route path="/home" element={<Home />} />
              <Route path="/lesson/:lessonId" element={<Lesson />} />
              <Route path="/guide" element={<Guide />} />
            </>
          ) : (
            <>
              <Route path="/admin" element={<AdminAthletes />} />
              <Route path="/admin/athletes/:athleteId" element={<AdminAthlete />} />
              <Route path="/admin/settings" element={<AdminSettings />} />
              <Route path="/check" element={<Check />} />
              <Route path="/library" element={<Library />} />
              <Route path="/library/:docId" element={<Library />} />
              <Route path="/architecture" element={<Architecture />} />
            </>
          )}
          <Route path="/ask" element={<Ask />} />
          <Route path="*" element={<Navigate to={HOME_BY_ROLE[who.role]} replace />} />
        </Route>
      </Routes>
    </SessionContext.Provider>
  );
}
