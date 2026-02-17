
// Edit Mode Toggle


function enterEditMode() {
    const display = document.getElementById("displayMode");
    const edit = document.getElementById("editMode");

    if (display && edit) {
        display.style.display = "none";
        edit.style.display = "block";
    }
}

function cancelEditMode() {
    const display = document.getElementById("displayMode");
    const edit = document.getElementById("editMode");

    if (display && edit) {
        display.style.display = "block";
        edit.style.display = "none";
    }
}


// Profile Image Preview (Frontend Only)


function triggerImageUpload() {
    const input = document.getElementById("imageUpload");
    if (input) {
        input.click();
    }
}

function handleImageUpload(event) {
    const file = event.target.files[0];

    if (file) {
        const reader = new FileReader();

        reader.onload = function (e) {
            const img = document.getElementById("profileImg");
            if (img) {
                img.src = e.target.result;
            }
        };

        reader.readAsDataURL(file);
    }
}

// Notification System 

function showNotification(message, type = "success") {
    const notification = document.getElementById("notification");
    const notificationText = document.getElementById("notificationText");

    if (notification && notificationText) {
        notificationText.textContent = message;
        notification.className = `notification show ${type}`;

        setTimeout(() => {
            notification.classList.remove("show");
        }, 3000);
    }
}


// Safe Image Fallback


document.addEventListener("DOMContentLoaded", function () {
    const profileImg = document.getElementById("profileImg");

    if (profileImg) {
        profileImg.onerror = function () {
            this.src =
                "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='400' height='400'%3E%3Crect fill='%23e5e5e5' width='400' height='400'/%3E%3Ctext fill='%23404040' font-size='120' x='50%25' y='50%25' text-anchor='middle' dy='.3em'%3EUser%3C/text%3E%3C/svg%3E";
        };
    }
});

