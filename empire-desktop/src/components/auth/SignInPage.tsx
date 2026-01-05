import { SignIn } from '@clerk/clerk-react'

/**
 * Sign-in page component
 * Uses Clerk's pre-built SignIn component with custom styling
 */
export function SignInPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-empire-bg">
      <div className="flex flex-col items-center space-y-8">
        {/* Empire Logo */}
        <div className="flex items-center space-x-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-empire-primary">
            <span className="text-2xl font-bold text-white">E</span>
          </div>
          <span className="text-2xl font-semibold text-white">Empire Desktop</span>
        </div>

        {/* Clerk Sign In */}
        <SignIn
          appearance={{
            elements: {
              rootBox: 'w-full max-w-md',
              card: 'bg-empire-sidebar border border-white/10 shadow-xl',
              headerTitle: 'text-white',
              headerSubtitle: 'text-gray-400',
              formFieldLabel: 'text-gray-300',
              formFieldInput: 'bg-empire-bg border-white/10 text-white placeholder:text-gray-500',
              formButtonPrimary: 'bg-empire-primary hover:bg-empire-primary/90',
              footerActionLink: 'text-empire-primary hover:text-empire-primary/80',
              identityPreviewText: 'text-white',
              identityPreviewEditButton: 'text-empire-primary',
              formFieldInputShowPasswordButton: 'text-gray-400',
              dividerLine: 'bg-white/10',
              dividerText: 'text-gray-500',
              socialButtonsBlockButton: 'border-white/20 bg-empire-sidebar hover:bg-white/10',
              socialButtonsBlockButtonText: 'text-white font-medium',
              socialButtonsBlockButtonArrow: 'text-white',
              socialButtonsProviderIcon: 'brightness-0 invert',
            },
            variables: {
              colorText: '#ffffff',
              colorTextOnPrimaryBackground: '#ffffff',
              colorTextSecondary: '#9ca3af',
              colorInputText: '#ffffff',
            },
          }}
          routing="hash"
          signUpUrl="#/sign-up"
          forceRedirectUrl="#/"
        />

        {/* Footer */}
        <p className="text-sm text-gray-500">
          Enterprise Knowledge Base Assistant
        </p>
      </div>
    </div>
  )
}

export default SignInPage
