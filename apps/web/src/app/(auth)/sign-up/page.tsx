import { Suspense } from "react";
import { AuthForm } from "@/components/auth/AuthForm";

export default function SignUpPage() {
  return (
    <Suspense>
      <AuthForm mode="sign-up" />
    </Suspense>
  );
}
