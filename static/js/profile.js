/**
 * Profile Manager
 * Handles user profile creation/editing
 */

class ProfileManager {
    constructor() {
        this.profileModal = document.getElementById('profileModal');
        this.profileForm = document.getElementById('profileForm');
        this.userId = localStorage.getItem('nakshatra_user_id') || 'user006';

        this.init();
    }

    init() {
        // Open profile modal
        document.getElementById('profileBtn').addEventListener('click', () => {
            this.openProfile();
        });

        // Close profile modal
        document.getElementById('closeProfile').addEventListener('click', () => {
            this.closeProfile();
        });

        // Close on outside click
        this.profileModal.addEventListener('click', (e) => {
            if (e.target === this.profileModal) {
                this.closeProfile();
            }
        });

        // Form submission
        this.profileForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveProfile();
        });

        // View chart button
        document.getElementById('viewChart').addEventListener('click', () => {
            this.viewChart();
        });

        // Load existing profile if available
        this.loadProfile();
    }

    async openProfile() {
        this.profileModal.classList.add('active');
    }

    closeProfile() {
        this.profileModal.classList.remove('active');
    }

    async loadProfile() {
        try {
            const profile = await apiClient.getUser(this.userId);
            this.populateForm(profile);
        } catch (error) {
            console.log('No existing profile found');
        }
    }

    populateForm(profile) {
        document.getElementById('userName').value = profile.name || '';
        document.getElementById('userEmail').value = profile.email || '';

        if (profile.birth_data) {
            document.getElementById('birthDate').value = profile.birth_data.date_of_birth || '';
            document.getElementById('birthTime').value = profile.birth_data.time_of_birth || '';
            document.getElementById('birthPlace').value = profile.birth_data.place_of_birth || '';
            document.getElementById('latitude').value = profile.birth_data.latitude || '';
            document.getElementById('longitude').value = profile.birth_data.longitude || '';
            document.getElementById('timezone').value = profile.birth_data.timezone || 'UTC';
        }
    }

    async saveProfile() {
        const formData = this.getFormData();

        try {
            // Try to update first
            try {
                await apiClient.updateUser(this.userId, formData);
                this.showSuccess('Profile updated successfully!');
            } catch (updateError) {
                // If update fails, try creating
                await apiClient.createUser({
                    user_id: this.userId,
                    ...formData
                });
                this.showSuccess('Profile created successfully!');
            }

            // Close modal after delay
            setTimeout(() => this.closeProfile(), 1500);
        } catch (error) {
            this.showError(error.message);
        }
    }

    getFormData() {
        return {
            name: document.getElementById('userName').value,
            email: document.getElementById('userEmail').value || null,
            birth_data: {
                date_of_birth: document.getElementById('birthDate').value,
                time_of_birth: document.getElementById('birthTime').value + ':00', // Add seconds
                place_of_birth: document.getElementById('birthPlace').value || null,
                latitude: parseFloat(document.getElementById('latitude').value),
                longitude: parseFloat(document.getElementById('longitude').value),
                timezone: document.getElementById('timezone').value
            }
        };
    }

    async viewChart() {
        const birthData = {
            date_of_birth: document.getElementById('birthDate').value,
            time_of_birth: document.getElementById('birthTime').value + ':00',
            latitude: parseFloat(document.getElementById('latitude').value),
            longitude: parseFloat(document.getElementById('longitude').value),
            timezone: document.getElementById('timezone').value,
            system: 'vedic'
        };

        try {
            const chart = await apiClient.calculateChart(birthData);
            this.displayChart(chart);
        } catch (error) {
            this.showError('Error calculating chart: ' + error.message);
        }
    }

    displayChart(chart) {
        // Create chart display
        const chartHTML = `
            <div style="padding: 1rem; background: rgba(99, 102, 241, 0.1); border-radius: 12px; margin-top: 1rem;">
                <h4 style="margin-bottom: 1rem;">Your Birth Chart</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
                    <div><strong>Lagna:</strong> ${chart.lagna}</div>
                    <div><strong>Rashi:</strong> ${chart.rashi}</div>
                    <div><strong>Nakshatra:</strong> ${chart.nakshatra}</div>
                    <div><strong>Dasha:</strong> ${chart.dasha.current}</div>
                </div>
            </div>
        `;

        // Insert before form actions
        const existingChart = this.profileForm.querySelector('.chart-display');
        if (existingChart) {
            existingChart.innerHTML = chartHTML;
        } else {
            const chartDiv = document.createElement('div');
            chartDiv.className = 'chart-display';
            chartDiv.innerHTML = chartHTML;
            this.profileForm.querySelector('.form-actions').before(chartDiv);
        }
    }

    showSuccess(message) {
        // Simple alert for now - could be improved with toast notifications
        alert(message);
    }

    showError(message) {
        alert('Error: ' + message);
    }
}

// Initialize when DOM is ready
let profileManager;
document.addEventListener('DOMContentLoaded', () => {
    profileManager = new ProfileManager();
});
