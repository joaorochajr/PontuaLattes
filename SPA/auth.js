const form = document.getElementById('auth-form');
const statusBox = document.getElementById('status');
const submitButton = document.getElementById('submit-button');


const isLogin = window.location.pathname.includes('login.html');
const endpoint = isLogin ? '/api/login' : '/api/register';

function setStatus(type, message) {
	statusBox.className = `status visible ${type}`;
	statusBox.textContent = message;
}

form.addEventListener('submit', async (event) => {
	event.preventDefault();
	
	const username = document.getElementById('username').value.trim();
	const password = document.getElementById('password').value;

	submitButton.disabled = true;
	setStatus('info', 'Processando...');

	try {
		const response = await fetch(endpoint, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ username, password }),
		});

		const resultado = await response.json();

		if (!response.ok || !resultado.success) {
			throw new Error(resultado.message || 'Erro na autenticação.');
		}

		setStatus('success', resultado.message || 'Sucesso!');

		if (isLogin) {
           
			localStorage.setItem('auth_token', resultado.token);
			window.location.href = '/index.html'; 
		} else {
           
			setTimeout(() => window.location.href = '/login.html', 1500);
		}
	} catch (error) {
		setStatus('error', error.message);
	} finally {
		submitButton.disabled = false;
	}
});