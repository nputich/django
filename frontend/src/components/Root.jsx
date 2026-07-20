import { Navigate } from "react-router-dom";
import { ensureValidSession } from "../auth";
import Login from "../pages/Login";

function Root() {
  if (ensureValidSession()) {
    return <Navigate to="/dashboard" replace />;
  }
  return <Login />;
}

export default Root;
