---
title: 'Ropewalk Repository: Workstation Neovim Configuration'
repo_slug: dotfiles/workstation
remote_origin: git@github.com:user/dotfiles.git
dotfile_target_path: ~/.config/nvim
$pkm:
  id: urn:uuid:01a0adb6-d2dc-74b8-8dd5-4a919225230e
  realm: ropewalk
  created_at: '2026-09-16T12:00:00Z'
  updated_at: '2026-09-16T12:00:00Z'
  relations:
    assignedToContact: urn:yeoman:contact:0191fa30-1025-7000-8000-000000000025
---

# Ropewalk Repository: Workstation Neovim Configuration

Configuration management record for editor dotfiles and automated symlink deployment.

## Dotfile Spec
Repo: `dotfiles/workstation` -> `~/.config/nvim`

## Transcluded Setup Instructions
![[ropewalk/configs/neovim#treesitter-setup]]

## Synchronization Pipeline
Automated health checks ensure Lua runtime and Treesitter parsers compile on pull.
^ropewalk-nvim-config
