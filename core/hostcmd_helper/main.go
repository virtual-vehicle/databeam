package main

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"log"
	"net"
	"os"
	"os/exec"
	"os/signal"
	"strings"
)

const SockAddr = "/tmp/databeam_hostcmd.sock"

func messageHandler(c_signal chan<- os.Signal, c net.Conn) {
	log.Printf("Client connected [%s]", c.RemoteAddr().Network())
	received := make([]byte, 0)
	for {
		buf := make([]byte, 512)
		count, err := c.Read(buf)

		received = append(received, buf[:count]...)

		if err != nil {
			if err != io.EOF {
				log.Println("Error on read: %s", err)
			}
			break // received EOF - done
		}
		log.Println("no error on message reconstruct:", count)
	}
	log.Println("command message:", string(received))
	c.Close()

	if string(received) == "dotheshutdown" {
		log.Println("DO SHUTDOWN")

		if err := exec.Command("poweroff").Run(); err != nil {
			log.Println("Failed to initiate shutdown:", err)
		}
		log.Println("exit from command handler")
		c_signal <- os.Interrupt

	} else if string(received) == "dothereboot" {
		log.Println("DO REBOOT")

		if err := exec.Command("reboot").Run(); err != nil {
			log.Println("Failed to initiate reboot:", err)
		}
		log.Println("exit from command handler")
		c_signal <- os.Interrupt

	} else if string(received) == "dothedockerrestart" {
		log.Println("DO DOCKER RESTART")

		if err := exec.Command("systemctl", "restart", "databeam.service").Run(); err != nil {
			log.Println("Failed to initiate docker restart:", err)
		} else {
			log.Println("Docker restart successful")
		}

	} else if string(received) == "dothedockerpull" {
		log.Println("DO DOCKER PULL")

		cmd := exec.Command("docker", "compose", "--env-file", "/opt/databeam/.env", "-f", "/opt/databeam/docker-compose.yml", "pull")
		var outb, errb bytes.Buffer
		cmd.Stdout = &outb
		cmd.Stderr = &errb
		err := cmd.Run()
		if err != nil {
			fmt.Println("Stdout:", outb.String(), "Stderr:", errb.String())
			log.Println("Failed to initiate docker pull:", err)
		} else {
			log.Println("Docker pull successful")
		}

	} else if strings.Contains(string(received), "dothetimesync") {
		datestring := strings.Split(string(received), "#")[1]
		cmd := exec.Command("date", "+%Y-%m-%dT%H:%M:%S.%3NZ", "-u", "-s", datestring)
		//cmd := exec.Command("date", "+%Y-%m-%dT%H:%M:%S.%3NZ")
		log.Println(cmd)
		if err := cmd.Run(); err != nil {
			log.Println("Failed to set system time:", err)
		} else {
			log.Println("Set system time successful")
			cmd := exec.Command("hwclock", "-w")
			log.Println(cmd)
			if err := cmd.Run(); err != nil {
				log.Println("Failed to set RTC time:", err)
			} else {
				log.Println("Set hardware time successful")
			}
		}

	} else {
		log.Println("unrecognized command:", string(received))
	}
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lmicroseconds | log.Lshortfile)
	log.Println("hi")

	ctx := context.Background()
	// trap Ctrl+C and call cancel on the context
	ctx, cancel := context.WithCancel(ctx)
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt)
	signal.Notify(c, os.Kill)
	// this makes sure we do a propper shutdown when the app itself decides to exit
	defer func() {
		signal.Stop(c)
		cancel()
	}()
	defer log.Println("byebye")

	if err := os.RemoveAll(SockAddr); err != nil {
		log.Fatal(err)
		cancel()
	}
	lc := net.ListenConfig{}
	l, err := lc.Listen(ctx, "unix", SockAddr)
	if err != nil {
		log.Fatal("listen error:", err)
		cancel()
	}
	defer l.Close()

	// wait for interrupt and cancel context
	go func() {
		select {
		case <-c:
			l.Close()
			cancel()
		case <-ctx.Done():
			// close this goroutine when context died somewhere else
			return
		}
	}()

	for {
		// Accept new connections, dispatching them to messageHandler in a goroutine.
		conn, err := l.Accept()
		if err != nil {
			log.Println("accept error:", err)
			return // exit if socket is closed
		}

		messageHandler(c, conn)
	}
}
