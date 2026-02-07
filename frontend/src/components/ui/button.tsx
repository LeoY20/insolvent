import React from 'react';

type ButtonVariant = 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
type ButtonSize = 'default' | 'sm' | 'lg';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const variantClasses: Record<ButtonVariant, string> = {
  default: 'bg-primary-600 text-white hover:bg-primary-700',
  destructive: 'bg-red-600 text-white hover:bg-red-700',
  outline: 'border border-gray-300 bg-transparent hover:bg-gray-100 hover:text-gray-900',
  secondary: 'bg-gray-200 text-gray-800 hover:bg-gray-300',
  ghost: 'hover:bg-gray-100 hover:text-gray-900',
  link: 'text-primary-600 underline-offset-4 hover:underline',
};

const sizeClasses: Record<ButtonSize, string> = {
  default: 'h-10 py-2 px-4',
  sm: 'h-9 px-3 rounded-md text-sm',
  lg: 'h-11 px-8 rounded-md',
};

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className = '', variant = 'default', size = 'default', ...props }, ref) => {
    const baseClasses = 'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none';

    const classes = `${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`.trim();

    return (
      <button
        className={classes}
        ref={ref}
        {...props}
      />
    );
  }
);

Button.displayName = 'Button';

export { Button };
