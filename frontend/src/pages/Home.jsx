import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import Note from "../components/Note";
import AppLayout from "../components/layout/AppLayout";
import "../styles/Home.css";

function Home() {
    const [notes, setNotes] = useState([]);
    const [content, setContent] = useState("");
    const [title, setTitle] = useState("");

    useEffect(() => {
        getNotes();
    }, []);

    const getNotes = () => {
        api
            .get("/api/notes/")
            .then((res) => res.data)
            .then((data) => setNotes(data))
            .catch((err) => alert(err));
    };

    const deleteNote = (id) => {
        api
            .delete(`/api/notes/delete/${id}/`)
            .then((res) => {
                if (res.status === 204) getNotes();
                else alert("Failed to delete note.");
            })
            .catch((error) => alert(error));
    };

    const createNote = (e) => {
        e.preventDefault();
        api
            .post("/api/notes/", { content, title })
            .then((res) => {
                if (res.status === 201) {
                    setContent("");
                    setTitle("");
                    getNotes();
                } else {
                    alert("Failed to make note.");
                }
            })
            .catch((err) => alert(err));
    };

    return (
        <AppLayout>
            <div className="app-page">
                <div className="app-page-header">
                    <h1>Your notes</h1>
                    <Link to="/" className="app-page-link">
                        ← Organization lookup
                    </Link>
                </div>
                <div className="notes-feed">
                    {notes.length === 0 ? (
                        <p className="notes-empty">No notes yet. Create one below.</p>
                    ) : (
                        notes.map((note) => (
                            <Note
                                note={note}
                                onDelete={deleteNote}
                                key={note.id}
                            />
                        ))
                    )}
                </div>
                <form className="note-form" onSubmit={createNote}>
                    <h2>Create a note</h2>
                    <label htmlFor="title">Title</label>
                    <input
                        type="text"
                        id="title"
                        name="title"
                        required
                        onChange={(e) => setTitle(e.target.value)}
                        value={title}
                    />
                    <label htmlFor="content">Content</label>
                    <textarea
                        id="content"
                        name="content"
                        required
                        rows={4}
                        value={content}
                        onChange={(e) => setContent(e.target.value)}
                    />
                    <button type="submit" className="note-form-submit">
                        Post note
                    </button>
                </form>
            </div>
        </AppLayout>
    );
}

export default Home;
