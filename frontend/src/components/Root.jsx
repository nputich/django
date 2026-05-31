import { Navigate } from "react-router-dom";
import { isAccessTokenValid } from "../auth";
import Login from "../pages/Login";
import Home from "../pages/Home";
import ProtectedRoute from "./ProtectedRoute";

function Root() {
  if (isAccessTokenValid()) {
    return (
      <ProtectedRoute>
        <Home />
      </ProtectedRoute>
    );
  }
  return <Login />;
}

export default Root;
