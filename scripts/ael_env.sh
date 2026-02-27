# Source this in ~/.bashrc for explicit trust context.
# AEL_MACHINE controls prompt color only; authority decisions are made by
# scripts/authority_status.sh identity policy, not by this env var.

if [[ -z "${AEL_MACHINE:-}" ]]; then
  export AEL_MACHINE="UNKNOWN"
fi

if [[ "$AEL_MACHINE" == "A" ]]; then
  export PS1="\[\e[38;5;39m\][A|\u@\h \W]\$\[\e[0m\] "
elif [[ "$AEL_MACHINE" == "B" ]]; then
  export PS1="\[\e[38;5;208m\][B|\u@\h \W]\$\[\e[0m\] "
else
  export PS1="\[\e[38;5;196m\][?|\u@\h \W]\$\[\e[0m\] "
fi
