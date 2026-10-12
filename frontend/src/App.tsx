import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router";
import { api, type AthleteProfile, type SessionInfo } from "./api";
import { Shell } from "./components/Shell";
import { HOME_BY_ROLE, SessionContext, TABS_BY_ROLE } from "./session";
import { Architecture } from "./pages/Architecture";
import { Check } from "./pages/Check";
import { Learn } from "./pages/Learn";
import { Performance } from "./pages/Performance";
import { Start } from "./pages/Start";

export default function App() {
  const [who, setWho] = useState<SessionInfo | null | undefined>(undefined);
  const [demo, setDemo] = useState(false);
  const [profile, setProfile] = useState<AthleteProfile | null>(null);

  useEffect(() => {
    api.whoami().then(setWho, () => setWho(null));
    api.personas().then(() => setDemo(true), () => setDemo(false));
  }, []);

  const logout = useCallback(() => {
    setProfile(null);
    api.logout().finally(() => setWho(null));
  }, []);

  if (who === undefined) return null;
  if (who === null) return <Start onLogin={setWho} />;

  const tabs = TABS_BY_ROLE[who.role];
  return (
    <SessionContext.Provider value={{ who, demo, logout, profile, setProfile }}>
      <Routes>
        <Route element={<Shell />}>
          {tabs.includes("performance") && <Route path="/performance" element={<Performance />} />}
          <Route path="/check" element={<Check />} />
          <Route path="/learn" element={<Learn />} />
          <Route path="/architecture" element={<Architecture />} />
          <Route path="*" element={<Navigate to={HOME_BY_ROLE[who.role]} replace />} />
        </Route>
      </Routes>
    </SessionContext.Provider>
  );
}
