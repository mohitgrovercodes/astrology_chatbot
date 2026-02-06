/**
 * Chat Manager
 * Handles chat UI and message sending/receiving
 */

class ChatManager {
    constructor() {
        this.messagesContainer = document.getElementById('messagesContainer');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.statusText = document.getElementById('statusText');

        this.conversationHistory = [];
        this.userId = localStorage.getItem('nakshatra_user_id') || 'user011';

        this.init();
    }

    init() {
        // Event listeners
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Suggestion chips
        document.querySelectorAll('.suggestion-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                this.messageInput.value = chip.dataset.query;
                this.sendMessage();
            });
        });
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        // Clear input
        this.messageInput.value = '';

        // Show user message
        this.addMessage(message, 'user');

        // Show typing indicator
        this.setStatus('NakshatraAI is typing...');
        const typingIndicator = this.showTypingIndicator();

        try {
            console.log('userID:', this.userId);
            // Send to API
            const response = await apiClient.sendMessage(
                message,
                this.userId,
                this.conversationHistory
            );

            // Remove typing indicator
            typingIndicator.remove();

            // Show bot response
            this.addMessage(response.answer, 'bot', response);

            // Update conversation history
            this.conversationHistory.push(
                { role: 'user', content: message },
                { role: 'assistant', content: response.answer }
            );

            // Keep only last 10 messages
            if (this.conversationHistory.length > 20) {
                this.conversationHistory = this.conversationHistory.slice(-20);
            }

            this.setStatus('Ready');
        } catch (error) {
            typingIndicator.remove();
            this.showError(error.message);
            this.setStatus('Error - Ready to retry');
        }
    }

    addMessage(text, sender, metadata = null) {
        // Hide welcome message on first real message
        const welcome = this.messagesContainer.querySelector('.welcome-message');
        if (welcome && sender !== 'welcome') {
            welcome.style.display = 'none';
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = sender === 'user' ? '👤' : '✨';

        const content = document.createElement('div');
        content.className = 'message-content';
        content.textContent = text;

        // Add metadata if available
        if (metadata) {
            const time = document.createElement('div');
            time.className = 'message-time';
            time.textContent = `${metadata.intent} • ${metadata.processing_time.toFixed(2)}s`;
            content.appendChild(time);
        }

        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);

        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    showTypingIndicator() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot typing-message';
        messageDiv.innerHTML = `
            <div class="message-avatar">✨</div>
            <div class="message-content">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
        return messageDiv;
    }

    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'message bot';
        errorDiv.innerHTML = `
            <div class="message-avatar">⚠️</div>
            <div class="message-content" style="background: rgba(239, 68, 68, 0.1); border-color: #ef4444; color: #ef4444;">
                <strong>Error:</strong> ${message}<br>
                <small>Please check your API key and try again.</small>
            </div>
        `;
        this.messagesContainer.appendChild(errorDiv);
        this.scrollToBottom();
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    setStatus(text) {
        this.statusText.textContent = text;
    }

    clearConversation() {
        this.conversationHistory = [];
        this.messagesContainer.innerHTML = '';
        // Show welcome message again
        // ... (would need to recreate welcome HTML)
    }
}

// Initialize when DOM is ready
let chatManager;
document.addEventListener('DOMContentLoaded', () => {
    chatManager = new ChatManager();
});
