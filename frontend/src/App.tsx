import { Link, Route, Routes } from "react-router-dom";
import CreatePage from "./pages/CreatePage";
import DashboardPage from "./pages/DashboardPage";
import DetailPage from "./pages/DetailPage";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark">B</span>
          <span>Beshno</span>
        </Link>
        <nav className="topnav">
          <Link to="/">Dashboard</Link>
          <Link to="/create" className="btn btn-primary">
            + New podcast
          </Link>
        </nav>
      </header>

      <main className="content">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/create" element={<CreatePage />} />
          <Route path="/podcasts/:id" element={<DetailPage />} />
        </Routes>
      </main>

      <footer className="footer">
        Beshno · AI-personalised language-learning podcasts
      </footer>
    </div>
  );
}
