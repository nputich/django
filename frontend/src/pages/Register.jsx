import Form from "../components/Form"
import AuthLayout from "../components/layout/AuthLayout"

function Register() {
    return (
        <AuthLayout>
            <Form route="/api/user/register/" method="register" />
        </AuthLayout>
    )
}

export default Register
