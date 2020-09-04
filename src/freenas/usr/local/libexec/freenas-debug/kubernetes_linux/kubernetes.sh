#!/bin/sh

kubernetes_opt() { echo k; }
kubernetes_help() { echo "Dump Kubernetes Information"; }
kubernetes_directory() { echo "Kubernetes"; }
kubernetes_func()
{
	
	section_header "Kubernetes Configuration"
	midclt call kubernetes.config | jq .
	section_footer

	k8s_running="$(midclt call service.started kubernetes)"
	if [ "$k8s_running" = "True" ]; then
		section_header "k3s kubectl cluster-info dump"
		k3s kubectl cluster-info dump
		section_footer

		section_header "docker ps -a"
		docker ps -a
		section_footer

		section_header "docker images -a"
		docker images -a
		section_footer
	fi
}
