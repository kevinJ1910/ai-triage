import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LoginPage from '../../app/login/page';

const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe('LoginPage Real-time Type Validation UI', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockPush.mockReset();
    localStorage.clear();
  });

  it('displays warning when invalid email is typed in login form', () => {
    render(<LoginPage />);

    const emailInput = screen.getByPlaceholderText('usuario@hospital.com');
    fireEvent.change(emailInput, { target: { value: 'notanemail' } });

    expect(screen.getByText(/Formato de correo electronico invalido/i)).toBeInTheDocument();

    // Type valid email - warning disappears
    fireEvent.change(emailInput, { target: { value: 'doctor@hospital.com' } });
    expect(screen.queryByText(/Formato de correo electronico invalido/i)).not.toBeInTheDocument();
  });

  it('displays password mismatch warning in register form', () => {
    render(<LoginPage />);

    // Switch to register tab
    const registerTabBtn = screen.getByRole('button', { name: 'Registro de Personal' });
    fireEvent.click(registerTabBtn);

    const passwordInput = screen.getByPlaceholderText('Min. 8 car.');
    const confirmInput = screen.getByPlaceholderText('Repetir clave');

    fireEvent.change(passwordInput, { target: { value: 'Secret123!' } });
    fireEvent.change(confirmInput, { target: { value: 'Different123!' } });

    expect(screen.getByText('Las contrasenas no coinciden.')).toBeInTheDocument();

    // Fix mismatch
    fireEvent.change(confirmInput, { target: { value: 'Secret123!' } });
    expect(screen.queryByText('Las contrasenas no coinciden.')).not.toBeInTheDocument();
  });

  it('prevents submission when invalid email is entered', async () => {
    render(<LoginPage />);

    const emailInput = screen.getByPlaceholderText('usuario@hospital.com');
    const passwordInput = screen.getByPlaceholderText('••••••••');
    const submitBtn = screen.getByRole('button', { name: /Ingresar al Sistema/i });

    fireEvent.change(emailInput, { target: { value: 'bademail' } });
    fireEvent.change(passwordInput, { target: { value: 'ValidPass123!' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Formato de correo electronico invalido/i)).toBeInTheDocument();
    });

    expect(mockPush).not.toHaveBeenCalled();
  });
});
