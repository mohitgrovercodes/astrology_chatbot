/**
 * Main App Controller
 * Handles theme, settings, and global app state
 */

class App {
    constructor() {
        this.theme = localStorage.getItem('nakshatra_theme') || 'light';
        this.init();
    }

    init() {
        // Apply saved theme
        this.applyTheme();

        // Theme toggle
        document.getElementById('themeToggle').addEventListener('click', () => {
            this.toggleTheme();
        });

        // Check API key on load
        this.checkAPIKey();

        // Check API health
        this.checkHealth();

        // Validate user session
        this.checkUser();
    }

    async checkUser() {
        const userId = localStorage.getItem('nakshatra_user_id');
        if (!userId) return; // Will default to user011 in other files

        try {
            await apiClient.getUser(userId);
            console.log(`✅ User ${userId} validated`);
        } catch (error) {
            console.warn(`⚠️ User ${userId} not found, resetting to default user011`);
            localStorage.setItem('nakshatra_user_id', 'user011');
            // Reload to apply changes across all components
            window.location.reload();
        }
    }

    toggleTheme() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        this.applyTheme();
        localStorage.setItem('nakshatra_theme', this.theme);
    }

    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);

        const themeToggle = document.getElementById('themeToggle');
        const icon = themeToggle.querySelector('.icon');
        icon.textContent = this.theme === 'light' ? '🌙' : '☀️';
    }

    checkAPIKey() {
        const apiKey = apiClient.getAPIKey();
        if (!apiKey) {
            this.promptForAPIKey();
        }
    }

    promptForAPIKey() {
        const key = prompt(
            'Please enter your API key:\n\n' +
            'You can find this in your .env file (VALID_API_KEYS)\n' +
            'Example: my-dev-key-123'
        );

        if (key) {
            apiClient.setAPIKey(key);
            this.showNotification('API key saved!', 'success');
        }
    }

    async checkHealth() {
        try {
            const health = await apiClient.healthCheck();
            console.log('✅ API Health:', health);

            if (health.status === 'healthy') {
                this.showNotification('Connected to NakshatraAI API', 'success');
            } else {
                this.showNotification('API is running but some components may be degraded', 'warning');
            }
        } catch (error) {
            console.error('❌ API Health Check Failed:', error);
            this.showNotification(
                'Cannot connect to API. Make sure the server is running on http://localhost:8000',
                'error'
            );
        }
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#6366f1'};
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
            z-index: 10000;
            animation: slideUp 0.3s ease;
        `;

        document.body.appendChild(notification);

        // Auto remove after 3 seconds
        setTimeout(() => {
            notification.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // Format date for display
    formatDate(date) {
        return new Date(date).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }

    // Format time for display
    formatTime(time) {
        return new Date(time).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }
}

// Initialize app when DOM is ready
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new App();
    console.log('🌟 NakshatraAI initialized');
});
