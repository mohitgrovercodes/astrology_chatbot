/**
 * API Client for NakshatraAI
 * Handles all communication with the FastAPI backend
 */

class APIClient {
    constructor() {
        this.baseURL = 'http://localhost:8000/api/v1';
        this.apiKey = this.getAPIKey();
    }

    /**
     * Get API key from localStorage
     */
    getAPIKey() {
        return localStorage.getItem('nakshatra_api_key') || '';
    }

    /**
     * Set API key and save to localStorage
     */
    setAPIKey(key) {
        this.apiKey = key;
        localStorage.setItem('nakshatra_api_key', key);
    }

    /**
     * Make authenticated request
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;

        const headers = {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        };

        // Add API key if available
        if (this.apiKey) {
            headers['X-API-Key'] = this.apiKey;
        }

        try {
            console.log('API Request:', {
                url,
                options,
                headers
            });

            const response = await fetch(url, {
                ...options,
                headers
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({
                    error: `HTTP ${response.status}: ${response.statusText}`
                }));
                throw new Error(error.error || error.detail || 'Request failed');
            }

            return await response.json();
        } catch (error) {
            console.log('API Error:', error);
            throw error;
        }
    }

    /**
     * Send chat message
     */
    async sendMessage(query, userId = 'user006', conversationHistory = []) {
        return this.request('/chat', {
            method: 'POST',
            body: JSON.stringify({
                query,
                user_id: userId,
                conversation_history: conversationHistory,
                include_chart_data: false
            })
        });
    }

    /**
     * Get user profile
     */
    async getUser(userId) {
        return this.request(`/user/${userId}`);
    }

    /**
     * Create user profile
     */
    async createUser(userData) {
        return this.request('/user', {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    }

    /**
     * Update user profile
     */
    async updateUser(userId, userData) {
        return this.request(`/user/${userId}`, {
            method: 'PUT',
            body: JSON.stringify(userData)
        });
    }

    /**
     * Calculate birth chart
     */
    async calculateChart(birthData) {
        return this.request('/calculate/chart', {
            method: 'POST',
            body: JSON.stringify(birthData)
        });
    }

    /**
     * Get current transits
     */
    async getCurrentTransits() {
        return this.request('/calculate/current-transits');
    }

    /**
     * Health check
     */
    async healthCheck() {
        return this.request('/health');
    }
}

// Export singleton instance
const apiClient = new APIClient();
