import { Suspense } from "react";
import { AuthForm } from "@/components/auth/AuthForm";

export default function SignInPage() {
  return (
    <Suspense>
      <AuthForm mode="sign-in" />
    </Suspense>
  );
}
