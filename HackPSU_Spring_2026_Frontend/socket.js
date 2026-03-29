const socket = io("http://localhost:5000");

function hostCrew() {
    socket.emit("host_crew");
}

function joinCrew() {
    const room = document.getElementById("roomInput").value;
    socket.emit("join_crew", { room });
}

function autoDeploy() {
    socket.emit("auto_deploy");
}

socket.on("host_created", ({ room, role }) => {
    window.location.href = `role${role}.html?room=${room}&role=${role}`;
});

socket.on("joined_room", ({ room, role }) => {
    window.location.href = `role${role}.html?room=${room}&role=${role}`;
});

socket.on("auto_deployed", ({ room, role }) => {
    window.location.href = `role${role}.html?room=${room}&role=${role}`;
});