import { Navigate } from "react-router-dom";

/** Same experience as home — keep the route for existing links. */
export default function EnterCode() {
  return <Navigate to="/" replace />;
}
