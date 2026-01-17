"""
Pytest configuration and fixtures for AI features tests.
"""
import pytest
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing without real API keys."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-for-testing")
    monkeypatch.setenv("APP_ENV", "testing")


@pytest.fixture
def sample_php_code():
    """Sample PHP code for testing."""
    return '''<?php

namespace App\\Http\\Controllers;

use Illuminate\\Http\\Request;
use App\\Models\\User;

class UserController extends Controller
{
    public function index()
    {
        $users = User::all();
        return view('users.index', compact('users'));
    }

    public function store(Request $request)
    {
        $validated = $request->validate([
            'name' => 'required|string|max:255',
            'email' => 'required|email|unique:users',
        ]);

        $user = User::create($validated);

        return redirect()->route('users.show', $user);
    }
}
'''


@pytest.fixture
def sample_blade_code():
    """Sample Blade template for testing."""
    return '''@extends('layouts.app')

@section('content')
<div class="container">
    <h1>{{ $title }}</h1>

    @foreach($users as $user)
        <div class="card">
            <h2>{{ $user->name }}</h2>
            <p>{{ $user->email }}</p>
        </div>
    @endforeach

    @if($users->isEmpty())
        <p>No users found.</p>
    @endif
</div>
@endsection
'''


@pytest.fixture
def sample_project_context():
    """Sample project context for testing."""
    return '''
## Project: TestApp

### Technology Stack
- **Backend Framework:** Laravel 11.0
- **PHP Version:** 8.3
- **Frontend Framework:** Vue 3.5
- **Database:** MySQL 8.0

### Codebase Statistics
- **Total Files:** 250
- **Total Lines:** 35,000

### Architecture Patterns
- Repository Pattern
- Service Layer
- Form Requests
'''
