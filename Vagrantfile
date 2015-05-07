# -*- mode: ruby -*-
# vi: set ft=ruby :


Vagrant.configure(2) do |config|

	# To create:
	# vagrant package --output scitran-vX.box
	#
	# To load from disk:
	# vagrant box add --name scitran-vX scitran-vX.box
	#
	# Docs:
	# http://docs.vagrantup.com/v2/cli/package.html

	# Box provided by Ubuntu
	config.vm.box = "trusty"
	config.vm.box_url = "https://cloud-images.ubuntu.com/vagrant/trusty/current/trusty-server-cloudimg-amd64-vagrant-disk1.box"
	config.vm.box_check_update = false

	# Port for humans and machines, respectively
	config.vm.network "forwarded_port", guest: 44300, host: 44300
	config.vm.network "forwarded_port", guest: 8080, host: 8080
	config.vm.network "forwarded_port", guest: 8000, host: 8000

	# Create a private network, which allows host-only access to the machine using a specific IP.
	config.vm.network "private_network", type: "dhcp"

	# Create a public network, which generally matched to bridged network.
	# Bridged networks make the machine appear as another physical device on your network.
	# config.vm.network "public_network"

	# Share an additional folder to the guest VM (host, guest, [options...])
	# Could add (owner: "root", group: "root",) or similar if needed
	config.vm.synced_folder ".", "/scitran", mount_options: ["rw"]

	config.vm.provider "virtualbox" do |vb|
		vb.gui = false

		# VBoxManage settings
		vb.customize ["modifyvm", :id,
			# Better I/O, disable if problems
			"--ioapic", "on",

			# Set this to the number of CPU cores you have
			"--cpus",   "4",

			# RAM allocation
			"--memory", "1024"
		]
	end

	# Install scitran
	config.vm.provision "shell", :path => "./scripts/install-simple.sh"

end
