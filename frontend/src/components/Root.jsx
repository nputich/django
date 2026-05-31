import { ensureValidSession } from "../auth";
import Login from "../pages/Login";
import Home from "../pages/Home";
import ProtectedRoute from "./ProtectedRoute";

function Root() {
  if (ensureValidSession()) {
    return (
      <ProtectedRoute>
        <Home />
      </ProtectedRoute>
    );
  }
  return <Login />;
}

export default Root;
