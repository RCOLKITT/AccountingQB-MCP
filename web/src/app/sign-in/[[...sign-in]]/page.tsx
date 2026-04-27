import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <main className="min-h-screen bg-[#0a0e1a] flex items-center justify-center px-6">
      <SignIn />
    </main>
  );
}
