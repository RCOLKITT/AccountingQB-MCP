import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <main className="min-h-screen bg-[#0a0e1a] flex items-center justify-center px-6">
      <SignUp />
    </main>
  );
}
