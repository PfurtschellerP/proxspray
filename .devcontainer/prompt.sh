# shellcheck shell=bash
# Two-line bash prompt for the proxspray dev container:
#
#   🌀 proxspray · /workspaces/proxspray  ⎇ main *+ ✘ 1
#   ❯
#
# Shows the working directory, git branch and state (* unstaged, + staged,
# % untracked, <> vs upstream) and the last exit code when it is non-zero.

[[ $- == *i* ]] || return 0

# shellcheck source=/dev/null
source /usr/lib/git-core/git-sh-prompt

GIT_PS1_SHOWDIRTYSTATE=1
GIT_PS1_SHOWUNTRACKEDFILES=1
GIT_PS1_SHOWUPSTREAM=auto
GIT_PS1_SHOWCOLORHINTS=1

__proxspray_prompt() {
    local status=$?
    local reset='\[\e[0m\]' bold='\[\e[1m\]' dim='\[\e[2m\]'
    local orange='\[\e[38;5;208m\]' cyan='\[\e[36m\]' red='\[\e[31m\]' green='\[\e[32m\]'

    local exit_info="" arrow_color=$green
    if ((status != 0)); then
        exit_info=" ${red}✘ ${status}${reset}"
        arrow_color=$red
    fi

    local before="${orange}${bold}🌀 proxspray${reset} ${dim}·${reset} ${cyan}\w${reset}"
    local after="${exit_info}\n${arrow_color}${bold}❯${reset} "

    __git_ps1 "$before" "$after" "  ⎇ %s"
}

PROMPT_COMMAND=__proxspray_prompt
