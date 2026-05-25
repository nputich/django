import Form from "../components/Form"
import AuthLayout from "../components/layout/AuthLayout"

function Login() {
    return (
        <AuthLayout>
            <Form route="/api/token/" method="login" />
        </AuthLayout>
    )
}

export default Login
