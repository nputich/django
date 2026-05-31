import { useState, useEffect } from "react";
import api from "../api";
import Note from "../components/Note";
import AppHeader from "../components/AppHeader";
import { clearAuth } from "../auth";
import "../styles/Home.css";

function Home() {
    const [notes, setNotes] = useState([]);
    const [content, setContent] = useState("");
    const [title, setTitle] = useState("");

    useEffect(() => {
        getNotes();
    }, []);

    const handleAuthError = () => {
        clearAuth();
        if (window.location.pathname !== "/") {
            window.location.replace("/");
        }
    };

    const getNotes = () => {
        api
            .get("/api/notes/")
            .then((res) => res.data)
            .then((data) => setNotes(data))
            .catch((err) => {
                if (err.response?.status === 401) {
                    handleAuthError();
                    return;
                }
                const message =
                    err.response?.data?.detail ||
                    err.message ||
                    "Failed to load notes.";
                alert(message);
            });
    };

    const deleteNote = (id) => {
        api
            .delete(`/api/notes/delete/${id}/`)
            .then((res) => {
                if (res.status === 204) alert("Note deleted!");
                else alert("Failed to delete note.");
                getNotes();
            })
            .catch((err) => {
                if (err.response?.status === 401) handleAuthError();
                else alert(err.response?.data?.detail || "Failed to delete note.");
            });
    };

    const createNote = (e) => {
        e.preventDefault();
        api
            .post("/api/notes/", { content, title })
            .then((res) => {
                if (res.status === 201) alert("Note created!");
                else alert("Failed to make note.");
                getNotes();
            })
            .catch((err) => {
                if (err.response?.status === 401) handleAuthError();
                else alert(err.response?.data?.detail || "Failed to create note.");
            });
    };

    return (
        <div className="app-page">
            <AppHeader />
            <main className="app-content">
            <div>
                <h2>Notes</h2>
                {notes.map((note) => (
                    <Note note={note} onDelete={deleteNote} key={note.id} />
                ))}
            </div>
            <h2>Create a Note</h2>
            <form onSubmit={createNote}>
                <label htmlFor="title">Title:</label>
                <br />
                <input
                    type="text"
                    id="title"
                    name="title"
                    required
                    onChange={(e) => setTitle(e.target.value)}
                    value={title}
                />
                <label htmlFor="content">Content:</label>
                <br />
                <textarea
                    id="content"
                    name="content"
                    required
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                ></textarea>
                <br />
                <input type="submit" value="Submit"></input>
            </form>
            </main>
        </div>
    );
}

export default Home;
